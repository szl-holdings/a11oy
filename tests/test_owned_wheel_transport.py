# SPDX-License-Identifier: Apache-2.0
"""Offline regressions for the build-only owned-wheel transport."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/fetch_owned_khipu_wheel.py"
WORKFLOW = ROOT / ".github/workflows/llama-wheel-guard.yml"


def load():
    spec = importlib.util.spec_from_file_location("owned_wheel_transport_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Response(io.BytesIO):
    status = 200

    def geturl(self):
        return "https://release-assets.githubusercontent.com/example/wheel"


def fixture_transport(monkeypatch, body=b"valid wheel fixture"):
    module = load()
    expected = b"valid wheel fixture"
    module.EXPECTED_SIZE = len(expected)
    module.EXPECTED_SHA256 = hashlib.sha256(expected).hexdigest()
    calls = []

    def open_request(request, timeout):
        calls.append((request.full_url, timeout))
        return Response(body)

    monkeypatch.setattr(
        module.urllib.request,
        "build_opener",
        lambda *a: SimpleNamespace(open=open_request),
    )
    return module, calls


def test_verified_bytes_are_published_once(tmp_path, monkeypatch):
    module, calls = fixture_transport(monkeypatch)
    target = module.fetch_wheel(tmp_path)
    assert target.read_bytes() == b"valid wheel fixture"
    assert calls == [(module.URL, 20.0)]
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("body", [b"short", b"x" * 19, b"too long" * 4])
def test_bad_bytes_never_replace_previous_wheel(tmp_path, monkeypatch, body):
    module, _ = fixture_transport(monkeypatch, body)
    existing = tmp_path / module.WHEEL
    existing.write_bytes(b"previous verified copy")
    with pytest.raises(ValueError):
        module.fetch_wheel(tmp_path)
    assert existing.read_bytes() == b"previous verified copy"
    assert list(tmp_path.iterdir()) == [existing]


def test_interrupted_stream_removes_temporary_file(tmp_path, monkeypatch):
    module, _ = fixture_transport(monkeypatch)

    class Broken(Response):
        def read(self, size=-1):
            raise TimeoutError("fixture interruption")

    monkeypatch.setattr(
        module.urllib.request,
        "build_opener",
        lambda *a: SimpleNamespace(open=lambda *a, **kw: Broken()),
    )
    with pytest.raises(TimeoutError):
        module.fetch_wheel(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_elapsed_budget_stops_download(tmp_path, monkeypatch):
    module, _ = fixture_transport(monkeypatch)
    ticks = iter((0.0, 121.0))
    monkeypatch.setattr(module.time, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError):
        module.fetch_wheel(tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/file",
        "https://example.com/file",
        "https://github.com.evil.invalid/file",
        "https://github.com:8443/file",
        "https://user@github.com/file",
        "file:///tmp/wheel",
    ],
)
def test_redirect_rejected_before_following(url):
    module = load()
    with pytest.raises(ValueError):
        module.ReleaseRedirects().redirect_request(
            urllib.request.Request(module.URL), None, 302, "Found", {}, url
        )


def test_official_https_release_redirect_is_accepted():
    module = load()
    url = "https://release-assets.githubusercontent.com/example/wheel?signature=fixture"
    redirected = module.ReleaseRedirects().redirect_request(
        urllib.request.Request(module.URL), None, 302, "Found", {}, url
    )
    assert redirected.full_url == url


def test_release_identity_remains_pinned():
    module = load()
    assert module.EXPECTED_SIZE == 23912624
    assert (
        module.EXPECTED_SHA256
        == "d172f3d3c8cdd194c3c47c71cb077ed6e61354a2d0f939ceeac0c8fd29999596"
    )
    assert module.URL == (
        "https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.35/"
        "llama_cpp_python-0.3.35-py3-none-manylinux2014_x86_64."
        "manylinux_2_17_x86_64.whl"
    )


def test_dockerfile_ships_transport_without_remote_add():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert (
        "COPY scripts/fetch_owned_khipu_wheel.py /tmp/fetch_owned_khipu_wheel.py"
        in text
    )
    assert "RUN python3 /tmp/fetch_owned_khipu_wheel.py" in text
    assert "ADD --checksum=" not in text
    assert "RUN python3 <<'WHEELCHK'" in text
    assert "23912624" in text and "libc.so.6" in text
    assert "COPY a11oy_governed_cortex.py" in text


def test_guard_validates_and_executes_source_owned_transport():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "'scripts/fetch_owned_khipu_wheel.py'" in text
    assert "'tests/test_owned_wheel_transport.py'" in text
    assert "Resolve the source-owned official wheel contract" in text
    assert 'spec_from_file_location("owned_wheel_contract"' in text
    assert 'module.fetch_wheel(Path(os.environ["RUNNER_TEMP"]))' in text
    assert "expected exactly one official wheel ADD contract" not in text
    assert "sha256sum -c -" in text
    assert 'assert b"libc.so.6" in data' in text
