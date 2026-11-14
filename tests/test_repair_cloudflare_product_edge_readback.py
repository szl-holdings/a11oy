"""Readback verification for the Cloudflare product-edge controller.

Cloudflare's content/v2 endpoint returns module Workers inside a
multipart/form-data envelope; the controller must compare the extracted
module source, not the envelope bytes.
"""
import io
import sys
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import repair_cloudflare_product_edge as controller

SOURCE = b"export default { async fetch() { return new Response('ok'); } };\n"


class _FakeResponse:
    def __init__(self, body: bytes):
        self._stream = io.BytesIO(body)

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _envelope(source: bytes, *, boundary: str = "----cfboundary123") -> bytes:
    head = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="worker.mjs"; filename="worker.mjs"\r\n'
        "Content-Type: application/javascript+module\r\n"
        "\r\n"
    ).encode()
    return head + source + f"\r\n--{boundary}--\r\n".encode()


def _present(monkeypatch):
    monkeypatch.setattr(
        controller,
        "request_json",
        lambda method, path, bearer: {
            "result_info": {"total_pages": 1},
            "result": [{"id": "script"}, {"id": "other"}],
        },
    )


def test_multipart_readback_yields_identical(monkeypatch):
    _present(monkeypatch)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout: _FakeResponse(_envelope(SOURCE)),
    )
    assert controller.inspect_worker_script("acct", "tok", "script", SOURCE) == "identical"


def test_raw_readback_yields_identical(monkeypatch):
    _present(monkeypatch)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout: _FakeResponse(SOURCE),
    )
    assert controller.inspect_worker_script("acct", "tok", "script", SOURCE) == "identical"


def test_multipart_readback_mismatch_collides(monkeypatch):
    _present(monkeypatch)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout: _FakeResponse(_envelope(SOURCE + b"drift")),
    )
    with pytest.raises(controller.EdgeError) as exc:
        controller.inspect_worker_script("acct", "tok", "script", SOURCE)
    assert exc.value.args[0] == "WORKER_SCRIPT_NAME_COLLISION"


def test_malformed_multipart_fails_closed(monkeypatch):
    _present(monkeypatch)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout: _FakeResponse(b"--boundary\r\nno-blank-line"),
    )
    with pytest.raises(controller.EdgeError) as exc:
        controller.inspect_worker_script("acct", "tok", "script", SOURCE)
    assert exc.value.args[0] == "WORKER_SCRIPT_READBACK_MALFORMED_MULTIPART"


def test_module_bytes_helper_rejects_unterminated_envelope():
    with pytest.raises(controller.EdgeError) as exc:
        controller._module_bytes_from_readback(b"--b\r\n\r\npayload")
    assert exc.value.args[0] == "WORKER_SCRIPT_READBACK_MALFORMED_MULTIPART"


def test_absent_short_circuits(monkeypatch):
    monkeypatch.setattr(
        controller,
        "request_json",
        lambda method, path, bearer: {
            "result_info": {"total_pages": 1},
            "result": [{"id": "other"}],
        },
    )
    assert controller.inspect_worker_script("acct", "tok", "script", SOURCE) == "absent"
