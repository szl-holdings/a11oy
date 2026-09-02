#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply the bounded managed-alert transport repair.

This branch-only helper writes the reviewed transport primitives, wires every
workflow that consumes the managed alert secret through the same explicit
normalizer, and upgrades the source-controlled relay workflow from test-only to
test/deploy/canary.  It is removed by its executor before the final PR diff.
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
SECRET_LINE = "SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}"
PRELUDE = "source scripts/managed_alert_env.sh &&"
CHECKOUT_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"

EXPECTED_WORKFLOWS = {
    "a11oy-api-health.yml",
    "alert-channel-watch.yml",
    "alert-relay-worker.yml",
    "dsse-receipts.yml",
    "gguf-weight-guard.yml",
    "hf-corpus-card-honesty.yml",
    "hf-corpus-freshness.yml",
    "hf-corpus-reverify.yml",
    "hf-drift-check.yml",
    "kev-feed-guard.yml",
    "llama-wheel-guard.yml",
    "phantom-required-check-guard.yml",
    "rekor-recheck.yml",
    "release-receipt-summary-guard.yml",
    "release-receipt-verify.yml",
    "scap-scan.yml",
    "sovereign-node-drop.yml",
}

ENDPOINT_PY = r'''#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Normalize the managed alert endpoint without exposing its opaque topic.

The historical managed secret used the static proof-registry host
``a11oy.net``.  That host must remain non-receiving for ordinary traffic.  The
source-controlled alert relay owns ``ntfy.a11oy.net`` instead.  This module
performs one narrow, explicit migration of the exact legacy hostname while
preserving the opaque path and query byte-for-byte.  Lookalikes are never
rewritten.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import urllib.parse

LEGACY_MANAGED_HOST = "a11oy.net"
MANAGED_RELAY_HOST = "ntfy.a11oy.net"
_TOPIC_HOSTS = {MANAGED_RELAY_HOST, "ntfy.sh"}


class ManagedAlertEndpointError(ValueError):
    """The managed endpoint cannot safely be used for delivery."""


def normalize_managed_endpoint(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ManagedAlertEndpointError("managed alert endpoint is missing")
    value = raw.strip()
    if len(value) > 4096:
        raise ManagedAlertEndpointError("managed alert endpoint exceeds the length bound")
    if any(character.isspace() for character in value):
        raise ManagedAlertEndpointError("managed alert endpoint contains whitespace")

    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ManagedAlertEndpointError("managed alert endpoint has an invalid port") from error

    if parsed.scheme != "https":
        raise ManagedAlertEndpointError("managed alert endpoint must use HTTPS")
    if not parsed.hostname:
        raise ManagedAlertEndpointError("managed alert endpoint has no hostname")
    if parsed.username or parsed.password:
        raise ManagedAlertEndpointError("embedded endpoint credentials are forbidden")
    if parsed.fragment:
        raise ManagedAlertEndpointError("endpoint fragments are forbidden")

    hostname = parsed.hostname.rstrip(".").lower()
    target_host = MANAGED_RELAY_HOST if hostname == LEGACY_MANAGED_HOST else hostname
    if target_host in _TOPIC_HOSTS and parsed.path in {"", "/"}:
        raise ManagedAlertEndpointError("managed ntfy endpoint requires an opaque topic path")

    if target_host == hostname:
        return value

    netloc = target_host + (f":{port}" if port is not None else "")
    return urllib.parse.urlunsplit(
        (parsed.scheme, netloc, parsed.path, parsed.query, "")
    )


def write_private(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n", encoding="utf-8")
    path.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env", default="SLACK_WEBHOOK_URL")
    args = parser.parse_args()
    try:
        normalized = normalize_managed_endpoint(os.environ.get(args.env, ""))
    except ManagedAlertEndpointError as error:
        # The error deliberately contains no endpoint, path, query, or token.
        raise SystemExit(f"managed alert endpoint rejected: {error}")
    write_private(args.output, normalized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

ENV_SH = r'''#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Source this file inside an alert-delivery step.  It changes only the current
# shell environment, emits no endpoint value, and masks the migrated value
# before any transport command can observe it.

_szl_prepare_managed_alert_endpoint() {
  if [ -z "${SLACK_WEBHOOK_URL:-}" ]; then
    return 0
  fi

  local root="${GITHUB_WORKSPACE:-$(pwd)}"
  local endpoint_file
  endpoint_file="$(mktemp)" || return 1
  chmod 600 "${endpoint_file}"

  if ! python3 "${root}/scripts/managed_alert_endpoint.py" --output "${endpoint_file}"; then
    rm -f "${endpoint_file}"
    echo "::error::Managed alert endpoint is invalid; no delivery was attempted."
    return 1
  fi

  local normalized
  if ! IFS= read -r normalized < "${endpoint_file}"; then
    rm -f "${endpoint_file}"
    echo "::error::Managed alert endpoint normalization produced no usable value."
    return 1
  fi
  rm -f "${endpoint_file}"
  if [ -z "${normalized}" ]; then
    echo "::error::Managed alert endpoint normalization produced an empty value."
    return 1
  fi

  echo "::add-mask::${normalized}"
  export SLACK_WEBHOOK_URL="${normalized}"
  unset normalized
}

_szl_prepare_managed_alert_endpoint
_szl_alert_endpoint_rc=$?
unset -f _szl_prepare_managed_alert_endpoint
return "${_szl_alert_endpoint_rc}" 2>/dev/null || exit "${_szl_alert_endpoint_rc}"
'''

ENDPOINT_TEST = r'''from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

from scripts.managed_alert_endpoint import (
    ManagedAlertEndpointError,
    normalize_managed_endpoint,
)


def test_exact_legacy_host_migrates_without_changing_opaque_topic() -> None:
    assert normalize_managed_endpoint(
        "https://a11oy.net/private%2Ftopic?access=opaque%2Bvalue"
    ) == "https://ntfy.a11oy.net/private%2Ftopic?access=opaque%2Bvalue"


def test_current_relay_and_other_valid_https_endpoints_are_unchanged() -> None:
    assert normalize_managed_endpoint(
        "https://ntfy.a11oy.net/private-topic"
    ) == "https://ntfy.a11oy.net/private-topic"
    assert normalize_managed_endpoint(
        "https://hooks.slack.com/services/a/b/c"
    ) == "https://hooks.slack.com/services/a/b/c"


def test_lookalikes_are_never_rewritten() -> None:
    value = "https://a11oy.net.evil.example/private-topic"
    assert normalize_managed_endpoint(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        "http://a11oy.net/private-topic",
        "https://a11oy.net/",
        "https://ntfy.a11oy.net/",
        "https://user:pass@a11oy.net/private-topic",
        "https://a11oy.net/private-topic#fragment",
        "https://a11oy.net/private topic",
    ],
)
def test_invalid_managed_endpoints_fail_closed(value: str) -> None:
    with pytest.raises(ManagedAlertEndpointError):
        normalize_managed_endpoint(value)


def test_cli_writes_private_file_and_never_prints_endpoint(tmp_path: Path) -> None:
    output = tmp_path / "endpoint"
    secret = "https://a11oy.net/private-topic?token=never-print"
    result = subprocess.run(
        [
            "python3",
            "scripts/managed_alert_endpoint.py",
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "SLACK_WEBHOOK_URL": secret},
        text=True,
        capture_output=True,
        check=True,
    )
    rendered = result.stdout + result.stderr
    assert secret not in rendered
    assert "private-topic" not in rendered
    assert output.read_text(encoding="utf-8").strip().startswith(
        "https://ntfy.a11oy.net/"
    )
    assert output.stat().st_mode & 0o077 == 0
'''

WORKFLOW_TEST = r'''from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
SECRET_LINE = "SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}"
PRELUDE = "source scripts/managed_alert_env.sh &&"
EXPECTED = {
    "a11oy-api-health.yml",
    "alert-channel-watch.yml",
    "alert-relay-worker.yml",
    "dsse-receipts.yml",
    "gguf-weight-guard.yml",
    "hf-corpus-card-honesty.yml",
    "hf-corpus-freshness.yml",
    "hf-corpus-reverify.yml",
    "hf-drift-check.yml",
    "kev-feed-guard.yml",
    "llama-wheel-guard.yml",
    "phantom-required-check-guard.yml",
    "rekor-recheck.yml",
    "release-receipt-summary-guard.yml",
    "release-receipt-verify.yml",
    "scap-scan.yml",
    "sovereign-node-drop.yml",
}


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _step_bounds(lines: list[str], index: int) -> tuple[int, int]:
    secret_indent = _indent(lines[index])
    start = None
    for position in range(index, -1, -1):
        stripped = lines[position].lstrip()
        if stripped.startswith("- ") and _indent(lines[position]) < secret_indent:
            start = position
            break
    assert start is not None
    step_indent = _indent(lines[start])
    end = len(lines)
    for position in range(start + 1, len(lines)):
        if not lines[position].strip():
            continue
        current_indent = _indent(lines[position])
        if current_indent < step_indent or (
            current_indent == step_indent and lines[position].lstrip().startswith("- ")
        ):
            end = position
            break
    return start, end


def test_every_managed_secret_consumer_uses_the_normalizer_in_its_own_step() -> None:
    actual = set()
    for path in sorted(WORKFLOW_DIR.glob("*.yml")):
        lines = path.read_text(encoding="utf-8").splitlines()
        secret_indexes = [
            index for index, line in enumerate(lines) if SECRET_LINE in line
        ]
        if not secret_indexes:
            continue
        actual.add(path.name)
        for index in secret_indexes:
            start, end = _step_bounds(lines, index)
            block = "\n".join(lines[start:end])
            assert PRELUDE in block, f"{path}: unmanaged alert secret consumer"
            before = "\n".join(lines[:start])
            job_prefix = before.rsplit("\n  ", 1)[-1]
            # Either the same job already checked out the repository or the
            # repair inserted a dedicated immutable checkout before this step.
            assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in before
    assert actual == EXPECTED


def test_relay_workflow_deploys_and_requires_a_real_post_deploy_canary() -> None:
    value = (WORKFLOW_DIR / "alert-relay-worker.yml").read_text(encoding="utf-8")
    assert "wrangler@4.128.0" in value
    assert "CLOUDFLARE_API_TOKEN" in value
    assert "ntfy.a11oy.net" in value
    assert "alert_channel_canary.py" in value
    assert "--send" in value
    assert "Enforce real delivery health" in value
'''

RELAY_WORKFLOW = r'''name: Alert relay worker

on:
  pull_request:
    paths:
      - '.github/workflows/alert-relay-worker.yml'
      - 'ops/alert-relay-worker/**'
      - 'scripts/alert_channel_canary.py'
      - 'scripts/managed_alert_endpoint.py'
      - 'scripts/managed_alert_env.sh'
      - 'tests/test_alert_channel_canary.py'
      - 'tests/test_alert_channel_static_registry_contract.py'
      - 'tests/test_managed_alert_endpoint.py'
      - 'tests/test_managed_alert_transport_workflows.py'
  push:
    branches: [main]
    paths:
      - '.github/workflows/alert-relay-worker.yml'
      - 'ops/alert-relay-worker/**'
      - 'scripts/alert_channel_canary.py'
      - 'scripts/managed_alert_endpoint.py'
      - 'scripts/managed_alert_env.sh'
      - 'tests/test_alert_channel_canary.py'
      - 'tests/test_alert_channel_static_registry_contract.py'
      - 'tests/test_managed_alert_endpoint.py'
      - 'tests/test_managed_alert_transport_workflows.py'
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: alert-relay-worker-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    name: Test fail-closed relay and migration contracts
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Harden runner
        uses: step-security/harden-runner@05e31511f85b41b11d1cf0ef85d0992719546e2c # v2.21.0
        with:
          egress-policy: audit
      - name: Checkout exact candidate
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - name: Set up Python
        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: '3.12'
      - name: Install exact core test dependencies
        run: pip install --require-hashes -r .github/requirements/ci-core.txt
      - name: Exercise relay and workflow contracts
        run: |
          node --test ops/alert-relay-worker/test/index.test.mjs
          pytest \
            tests/test_alert_channel_canary.py \
            tests/test_alert_channel_static_registry_contract.py \
            tests/test_managed_alert_endpoint.py \
            tests/test_managed_alert_transport_workflows.py \
            -q

  deploy:
    name: Deploy exact relay and prove one real delivery
    if: github.event_name != 'pull_request'
    needs: test
    runs-on: ubuntu-latest
    timeout-minutes: 15
    env:
      CI: 'true'
      CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN || secrets.CF_API_TOKEN || secrets.CLOUDFLARE_TOKEN }}
    steps:
      - name: Harden runner
        uses: step-security/harden-runner@05e31511f85b41b11d1cf0ef85d0992719546e2c # v2.21.0
        with:
          egress-policy: audit
      - name: Checkout exact protected source
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          ref: ${{ github.sha }}
          persist-credentials: false
      - name: Set up Node.js
        uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v6.1.0
        with:
          node-version: '22'
          check-latest: false
      - name: Set up Python
        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: '3.12'
      - name: Require a Cloudflare deployment credential
        shell: bash
        run: |
          set -euo pipefail
          if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
            echo "::error::No Cloudflare API token is configured for the relay deployment."
            exit 1
          fi
      - name: Deploy the exact source-controlled Worker and custom domain
        shell: bash
        run: >-
          npx --yes wrangler@4.128.0 deploy
          --config ops/alert-relay-worker/wrangler.jsonc
      - name: Wait only for the declared custom-domain DNS name
        shell: bash
        run: |
          python - <<'PY'
          import socket
          import time

          host = "ntfy.a11oy.net"
          for attempt in range(12):
              try:
                  socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
                  break
              except socket.gaierror:
                  if attempt == 11:
                      raise
                  time.sleep(5)
          PY
      - name: Run one bounded real delivery canary
        id: canary
        continue-on-error: true
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          ALERT_CHANNEL_MODE: ntfy
        shell: bash
        run: |
          source scripts/managed_alert_env.sh &&
          mkdir -p evidence
          set +e
          python scripts/alert_channel_canary.py \
            --output evidence/alert-channel-post-deploy.json \
            --mode ntfy \
            --send
          rc=$?
          echo "exit_code=${rc}" >> "$GITHUB_OUTPUT"
          exit 0
      - name: Upload secret-free delivery evidence
        if: always()
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: alert-relay-post-deploy-${{ github.run_id }}-${{ github.run_attempt }}
          path: evidence/alert-channel-post-deploy.json
          if-no-files-found: warn
          retention-days: 90
      - name: Enforce real delivery health
        if: always()
        env:
          EXIT_CODE: ${{ steps.canary.outputs.exit_code }}
        shell: bash
        run: |
          set -euo pipefail
          if [ "${EXIT_CODE:-missing}" != '0' ]; then
            echo "::error::The deployed relay did not prove one real 2xx delivery."
            exit 1
          fi
'''


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _step_bounds(lines: list[str], index: int) -> tuple[int, int]:
    secret_indent = _indent(lines[index])
    start = None
    for position in range(index, -1, -1):
        stripped = lines[position].lstrip()
        if stripped.startswith("- ") and _indent(lines[position]) < secret_indent:
            start = position
            break
    if start is None:
        raise RuntimeError(f"could not locate alert step around line {index + 1}")
    step_indent = _indent(lines[start])
    end = len(lines)
    for position in range(start + 1, len(lines)):
        if not lines[position].strip():
            continue
        current_indent = _indent(lines[position])
        if current_indent < step_indent or (
            current_indent == step_indent and lines[position].lstrip().startswith("- ")
        ):
            end = position
            break
    return start, end


def _job_start(lines: list[str], step_start: int) -> int:
    for position in range(step_start, -1, -1):
        stripped = lines[position].strip()
        if _indent(lines[position]) == 2 and stripped.endswith(":"):
            return position
    raise RuntimeError(f"could not locate job before line {step_start + 1}")


def _ensure_checkout_before_first_alert(lines: list[str]) -> list[str]:
    secret_indexes = [index for index, line in enumerate(lines) if SECRET_LINE in line]
    jobs: dict[int, list[int]] = {}
    for index in secret_indexes:
        step_start, _ = _step_bounds(lines, index)
        jobs.setdefault(_job_start(lines, step_start), []).append(step_start)

    insertions: list[tuple[int, list[str]]] = []
    for job_start, steps in jobs.items():
        first_step = min(steps)
        prior = "\n".join(lines[job_start:first_step])
        if f"actions/checkout@{CHECKOUT_SHA}" in prior:
            continue
        step_indent = _indent(lines[first_step])
        prefix = " " * step_indent
        nested = " " * (step_indent + 2)
        insertions.append(
            (
                first_step,
                [
                    f"{prefix}- name: Check out managed alert transport",
                    f"{nested}uses: actions/checkout@{CHECKOUT_SHA} # v7.0.1",
                    f"{nested}with:",
                    f"{nested}  persist-credentials: false",
                ],
            )
        )
    for position, content in sorted(insertions, reverse=True):
        lines[position:position] = content
    return lines


def _ensure_step_preludes(lines: list[str], path: Path) -> list[str]:
    secret_indexes = [index for index, line in enumerate(lines) if SECRET_LINE in line]
    run_indexes: set[int] = set()
    for index in secret_indexes:
        start, end = _step_bounds(lines, index)
        candidates = [
            position
            for position in range(start, end)
            if lines[position].lstrip().startswith("run:")
        ]
        if len(candidates) != 1:
            raise RuntimeError(
                f"expected one run block for managed alert step in {path}, found {len(candidates)}"
            )
        run_indexes.add(candidates[0])

    for run_index in sorted(run_indexes, reverse=True):
        start, end = _step_bounds(lines, run_index)
        if PRELUDE in "\n".join(lines[start:end]):
            continue
        stripped = lines[run_index].lstrip()
        run_indent = _indent(lines[run_index])
        prefix = " " * run_indent
        if stripped == "run:":
            raise RuntimeError(f"empty run key in {path}:{run_index + 1}")
        command = stripped[len("run:"):].strip()
        if command and command not in {"|", "|-", "|+", ">", ">-", ">+"}:
            lines[run_index] = f"{prefix}run: {PRELUDE} {command}"
        else:
            lines.insert(run_index + 1, " " * (run_indent + 2) + PRELUDE)
    return lines


def _patch_watch_contract() -> None:
    path = WORKFLOWS / "alert-channel-watch.yml"
    text = path.read_text(encoding="utf-8")
    anchor = "      - 'tests/test_alert_channel_workflow_contract.py'\n"
    additions = (
        "      - 'scripts/managed_alert_endpoint.py'\n"
        "      - 'scripts/managed_alert_env.sh'\n"
        "      - 'tests/test_managed_alert_endpoint.py'\n"
        "      - 'tests/test_managed_alert_transport_workflows.py'\n"
    )
    if "tests/test_managed_alert_endpoint.py" not in text:
        count = text.count(anchor)
        if count != 2:
            raise RuntimeError(f"expected two alert-watch path anchors, found {count}")
        text = text.replace(anchor, anchor + additions)
    old = (
        "          tests/test_alert_channel_canary.py\n"
        "          tests/test_alert_channel_workflow_contract.py\n"
        "          -q\n"
    )
    new = (
        "          tests/test_alert_channel_canary.py\n"
        "          tests/test_alert_channel_workflow_contract.py\n"
        "          tests/test_managed_alert_endpoint.py\n"
        "          tests/test_managed_alert_transport_workflows.py\n"
        "          -q\n"
    )
    if old not in text and new not in text:
        raise RuntimeError("alert-watch pytest contract anchor not found")
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    (ROOT / "scripts" / "managed_alert_endpoint.py").write_text(
        ENDPOINT_PY, encoding="utf-8"
    )
    (ROOT / "scripts" / "managed_alert_env.sh").write_text(
        ENV_SH, encoding="utf-8"
    )
    (ROOT / "tests" / "test_managed_alert_endpoint.py").write_text(
        ENDPOINT_TEST, encoding="utf-8"
    )
    (ROOT / "tests" / "test_managed_alert_transport_workflows.py").write_text(
        WORKFLOW_TEST, encoding="utf-8"
    )
    (WORKFLOWS / "alert-relay-worker.yml").write_text(
        RELAY_WORKFLOW, encoding="utf-8"
    )

    actual = {
        path.name
        for path in WORKFLOWS.glob("*.yml")
        if SECRET_LINE in path.read_text(encoding="utf-8")
    }
    if actual != EXPECTED_WORKFLOWS:
        raise RuntimeError(
            "managed alert workflow inventory drift: "
            f"missing={sorted(EXPECTED_WORKFLOWS - actual)} "
            f"unexpected={sorted(actual - EXPECTED_WORKFLOWS)}"
        )

    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if SECRET_LINE not in text:
            continue
        lines = text.splitlines()
        lines = _ensure_checkout_before_first_alert(lines)
        lines = _ensure_step_preludes(lines, path)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _patch_watch_contract()

    # The static proof-registry rejection remains intact.  Only shell steps that
    # explicitly source the managed normalizer can migrate the historical host.
    canary = (ROOT / "scripts" / "alert_channel_canary.py").read_text(encoding="utf-8")
    if '"a11oy.net": "a11oy.net is a static proof registry' not in canary:
        raise RuntimeError("static proof-registry fail-closed contract drifted")

    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if SECRET_LINE in text and PRELUDE not in text:
            raise RuntimeError(f"unmanaged alert workflow remains: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
