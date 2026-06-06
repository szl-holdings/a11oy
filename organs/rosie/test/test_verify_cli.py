"""Tests for rosie.console.verify_cli — the offline command-line verifier.

These tests exercise the CLI wrapper end to end: the three terminal verdicts
map to distinct exit codes, file and stdin input both work, and the --json
mode emits a parseable object. They make no network calls.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import json

import pytest

from src.console.receipt_verifier import sign_payload
from src.console.verify_cli import main

SAMPLE_PAYLOAD = {"spec": "szl.receipt/v1", "subject": "demo", "seq": 1}


def _write(path, obj_or_text) -> str:
    text = obj_or_text if isinstance(obj_or_text, str) else json.dumps(obj_or_text)
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_valid_envelope_exits_zero(tmp_path, capsys):
    env = sign_payload(SAMPLE_PAYLOAD)
    code = main([_write(tmp_path / "good.json", env)])
    out = capsys.readouterr().out
    assert code == 0
    assert "VALID" in out


def test_tampered_envelope_exits_two(tmp_path, capsys):
    env = sign_payload(SAMPLE_PAYLOAD)
    sig = env["signatures"][0]["sig"]
    env["signatures"][0]["sig"] = ("A" if sig[0] != "A" else "B") + sig[1:]
    code = main([_write(tmp_path / "bad.json", env)])
    out = capsys.readouterr().out
    assert code == 2
    assert "TAMPERED" in out


def test_malformed_input_exits_three(tmp_path, capsys):
    code = main([_write(tmp_path / "malformed.json", "{not json")])
    out = capsys.readouterr().out
    assert code == 3
    assert "MALFORMED" in out


def test_missing_file_exits_one(tmp_path, capsys):
    code = main([str(tmp_path / "does-not-exist.json")])
    err = capsys.readouterr().err
    assert code == 1
    assert "could not read input" in err


def test_stdin_input(monkeypatch, capsys):
    import io
    import sys

    env = sign_payload(SAMPLE_PAYLOAD)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(env)))
    code = main(["-"])
    assert code == 0
    assert "VALID" in capsys.readouterr().out


def test_json_mode_is_parseable(tmp_path, capsys):
    env = sign_payload(SAMPLE_PAYLOAD)
    code = main(["--json", _write(tmp_path / "good.json", env)])
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert code == 0
    assert parsed["verdict"] == "valid"
    assert parsed["ok"] is True
