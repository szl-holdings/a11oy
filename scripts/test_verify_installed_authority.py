# Copyright 2026 SZL Holdings - SPDX-License-Identifier: Apache-2.0
"""Offline tests for the installed-authority verifier (no network, no secrets)."""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import socket
import sys

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


SCRIPT = Path(__file__).with_name("verify_installed_authority.py")
SPEC = importlib.util.spec_from_file_location("verify_installed_authority_under_test", SCRIPT)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)

ROOT = SCRIPT.resolve().parent.parent
PINNED_PEM = (ROOT / verifier.PINNED_SIGNING_PUBLIC_KEY_PATH).read_bytes()
ORIGIN = verifier.CANONICAL_ORIGIN
NAMES = {verifier.SIGNING_SECRET, verifier.GDW_SECRET}
SECRET_SENTINEL = "-----BEGIN PRIVATE KEY-----synthetic-must-not-echo"


def static_fallback_pem() -> bytes:
    tree = ast.parse((ROOT / "szl_dsse.py").read_text(encoding="utf-8"))
    values = [node.value.value for node in tree.body if isinstance(node, ast.Assign)
              and getattr(node.targets[0], "id", "") == "COSIGN_PUBLIC_PEM"]
    assert len(values) == 1
    return values[0].strip().encode()


def public_pem(curve=ec.SECP256R1()) -> bytes:
    return ec.generate_private_key(curve).public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)


def serving(body: bytes, status: int = 200, calls: list | None = None):
    def get(url):
        if calls is not None:
            calls.append(url)
        if url.endswith("/cosign.pub"):
            return status, {"content-type": "text/plain"}, body
        return 200, {}, json.dumps({"git_sha": "b" * 40}).encode()
    return get


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("tests must stay offline")
    monkeypatch.setattr(verifier, "default_get", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def test_pinned_file_matches_hardcoded_fingerprint():
    assert verifier.pinned_fingerprint() == verifier.PINNED_SIGNING_KEY_DER_SHA256
    assert verifier.static_fallback_fingerprint() != verifier.PINNED_SIGNING_KEY_DER_SHA256


def test_pinned_runtime_key_is_verified():
    calls = []
    report = verifier.verify_installed_authority(NAMES, (), origin=ORIGIN, get=serving(PINNED_PEM, calls=calls))
    assert report["credential_authority_state"] == "VERIFIED"
    assert report["diagnostic_code"] == "INSTALLED_AUTHORITY_VERIFIED"
    assert report["signing"]["state"] == verifier.VERIFIED_PINNED_RUNTIME_KEY
    assert report["signing"]["served_fingerprint_sha256"] == verifier.PINNED_SIGNING_KEY_DER_SHA256
    assert report["signing"]["fresh_signature_verified"] is False
    assert report["gdw"]["state"] == verifier.GDW_NAME_PRESENT
    assert report["live_git_sha"] == "b" * 40
    assert report["origin"] == ORIGIN
    assert report["observed_at_start"] and report["observed_at_end"]
    assert calls[0] == ORIGIN + "/cosign.pub"
    assert report["secret_values_read"] is False and report["secret_values_written"] is False


def test_trailing_slash_origin_and_whitespace_pem_are_normalized():
    body = b"\n" + PINNED_PEM.replace(b"\n", b"\r\n") + b"\n"
    report = verifier.verify_signing_authority(ORIGIN + "/", serving(body))
    assert report["state"] == verifier.VERIFIED_PINNED_RUNTIME_KEY


def test_static_fallback_key_means_private_key_not_installed():
    report = verifier.verify_installed_authority(NAMES, (), origin=ORIGIN, get=serving(static_fallback_pem()))
    assert report["signing"]["state"] == verifier.SIGNING_KEY_NOT_INSTALLED
    assert report["credential_authority_state"] == "BLOCKED"
    assert report["diagnostic_code"] == "SIGNING_KEY_NOT_INSTALLED"


@pytest.mark.parametrize("body", [public_pem(), public_pem(ec.SECP384R1()), b"not a key", SECRET_SENTINEL.encode()])
def test_foreign_or_malformed_key_is_a_mismatch(body):
    report = verifier.verify_installed_authority(NAMES, (), origin=ORIGIN, get=serving(body))
    assert report["signing"]["state"] == verifier.SIGNING_KEY_MISMATCH
    assert report["credential_authority_state"] == "BLOCKED"
    assert "must-not-echo" not in json.dumps(report)


def raising(exc):
    def get(_url):
        raise exc
    return get


@pytest.mark.parametrize("get", [
    serving(PINNED_PEM, status=500),
    serving(PINNED_PEM, status=503),
    serving(PINNED_PEM, status=302),
    serving(PINNED_PEM, status=301),
    serving(PINNED_PEM, status=404),
    serving(PINNED_PEM + b"#" * (4 * 1024), status=200),
    serving(b"", status=200),
    raising(TimeoutError("synthetic timeout must-not-echo")),
    raising(OSError("synthetic transport must-not-echo")),
    lambda _url: (True, {}, PINNED_PEM),
    lambda _url: (200, {}, PINNED_PEM.decode()),
])
def test_unavailable_origin_is_unknown_never_verified(get):
    report = verifier.verify_installed_authority(NAMES, (), origin=ORIGIN, get=get)
    assert report["signing"]["state"] == verifier.ORIGIN_UNAVAILABLE
    assert report["credential_authority_state"] == "UNKNOWN"
    assert report["diagnostic_code"] == "AUTHORITY_ORIGIN_UNAVAILABLE"
    assert report["signing"]["served_fingerprint_sha256"] is None
    assert "must-not-echo" not in json.dumps(report)


def test_default_get_refuses_redirects_and_bounds_body(monkeypatch):
    # The real getter surfaces a 3xx as a non-200 status instead of following it.
    import http.server
    import threading

    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib hook
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:9/cosign.pub")
            self.end_headers()

        def log_message(self, *_args):
            pass

    monkeypatch.undo()  # this single test uses loopback only
    server = http.server.HTTPServer(("127.0.0.1", 0), Redirect)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    try:
        status, _headers, body = SPEC_DEFAULT_GET(f"http://127.0.0.1:{server.server_port}/cosign.pub")
    finally:
        server.server_close()
    assert status == 302 and body == b""


SPEC_DEFAULT_GET = verifier.default_get


@pytest.mark.parametrize("origin", ["https://attacker.hf.space", "http://szlholdings-a11oy.hf.space",
                                    "https://szlholdings-a11oy.hf.space/x", "", "https://user@szlholdings-a11oy.hf.space"])
def test_noncanonical_origin_is_never_fetched(origin):
    calls = []
    report = verifier.verify_installed_authority(NAMES, (), origin=origin, get=serving(PINNED_PEM, calls=calls))
    assert calls == []
    assert report["credential_authority_state"] == "UNKNOWN"
    assert report["diagnostic_code"] == "AUTHORITY_ORIGIN_NOT_CANONICAL"


def test_gdw_name_missing_is_blocking():
    report = verifier.verify_installed_authority({verifier.SIGNING_SECRET}, (), origin=ORIGIN, get=serving(PINNED_PEM))
    assert report["signing"]["state"] == verifier.VERIFIED_PINNED_RUNTIME_KEY
    assert report["gdw"] == {**report["gdw"], "state": verifier.GDW_CREDENTIALS_MISSING, "blocking": True}
    assert report["credential_authority_state"] == "BLOCKED"
    assert report["diagnostic_code"] == "GDW_CREDENTIALS_MISSING"


def test_signing_secret_name_missing_is_blocking_even_with_pinned_key():
    report = verifier.verify_installed_authority({verifier.GDW_SECRET}, (), origin=ORIGIN, get=serving(PINNED_PEM))
    assert report["credential_authority_state"] == "BLOCKED"
    assert report["diagnostic_code"] == "SIGNING_SECRET_MISSING"


@pytest.mark.parametrize("present", [False, True])
def test_github_reader_is_optional_and_never_blocking(present):
    names = NAMES | ({verifier.GITHUB_PUBLIC_READ_SECRET} if present else set())
    report = verifier.verify_installed_authority(names, (), origin=ORIGIN, get=serving(PINNED_PEM))
    assert report["github_public_reader"]["state"] == ("INSTALLED_NAME_ONLY" if present else "PUBLIC_ANONYMOUS")
    assert report["github_public_reader"]["blocking"] is False
    assert report["github_public_reader"]["value_verified"] is False
    assert report["credential_authority_state"] == "VERIFIED"


@pytest.mark.parametrize("variable", [verifier.SIGNING_SECRET, verifier.GDW_SECRET, verifier.GITHUB_PUBLIC_READ_SECRET])
def test_required_or_optional_name_collision_blocks(variable):
    report = verifier.verify_installed_authority(NAMES, {variable}, origin=ORIGIN, get=serving(PINNED_PEM))
    assert report["credential_authority_state"] == "BLOCKED"
    assert report["diagnostic_code"] == "PUBLIC_VARIABLE_COLLISION"


def test_pin_file_disagreeing_with_hardcoded_fingerprint_fails_closed(tmp_path):
    foreign = public_pem()
    pin = tmp_path / "pin.pub"
    pin.write_bytes(foreign)
    # Even when the runtime serves exactly the (tampered) pin file's key.
    report = verifier.verify_installed_authority(NAMES, (), origin=ORIGIN, get=serving(foreign), pinned_pem_path=pin)
    assert report["signing"]["state"] == verifier.SIGNING_KEY_MISMATCH
    assert report["signing"]["diagnostic_code"] == "PINNED_KEY_INCONSISTENT"
    assert report["credential_authority_state"] == "BLOCKED"


def test_hardcoded_fingerprint_disagreeing_with_pin_file_fails_closed(monkeypatch):
    monkeypatch.setattr(verifier, "PINNED_SIGNING_KEY_DER_SHA256", "0" * 64)
    report = verifier.verify_installed_authority(NAMES, (), origin=ORIGIN, get=serving(PINNED_PEM))
    assert report["signing"]["state"] == verifier.SIGNING_KEY_MISMATCH
    assert report["signing"]["diagnostic_code"] == "PINNED_KEY_INCONSISTENT"
    assert report["credential_authority_state"] == "BLOCKED"


@pytest.mark.parametrize("content", [b"", b"x" * (5 * 1024), b"not a pem"])
def test_missing_oversized_or_malformed_pin_file_fails_closed(tmp_path, content):
    pin = tmp_path / "pin.pub"
    pin.write_bytes(content)
    report = verifier.verify_signing_authority(ORIGIN, serving(PINNED_PEM), pin)
    assert report["state"] == verifier.SIGNING_KEY_MISMATCH
    assert report["diagnostic_code"] == "PINNED_KEY_INCONSISTENT"
    missing = verifier.verify_signing_authority(ORIGIN, serving(PINNED_PEM), tmp_path / "absent.pub")
    assert missing["diagnostic_code"] == "PINNED_KEY_INCONSISTENT"


def test_pin_equal_to_static_fallback_fails_closed(tmp_path):
    static = tmp_path / "szl_dsse.py"
    static.write_text("COSIGN_PUBLIC_PEM = " + repr(PINNED_PEM.decode()) + "\n", encoding="utf-8")
    report = verifier.verify_signing_authority(ORIGIN, serving(PINNED_PEM), static_source_path=static)
    assert report["state"] == verifier.SIGNING_KEY_MISMATCH
    assert report["diagnostic_code"] == "PINNED_KEY_INCONSISTENT"


def test_module_has_no_provider_import_and_report_is_bounded():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= set(sys.stdlib_module_names) | {"cryptography"}
    assert "huggingface_hub" not in imported
    report = verifier.verify_installed_authority(NAMES, (), origin=ORIGIN, get=serving(PINNED_PEM))
    assert len(json.dumps(report).encode()) < 4 * 1024
