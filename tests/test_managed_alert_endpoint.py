from __future__ import annotations

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
