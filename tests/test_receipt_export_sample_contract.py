"""The browser receipt verifier receives a prebuilt SAMPLE envelope."""

from __future__ import annotations

import ast
import asyncio
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_receipt_export_returns_prebuilt_sample_without_signing_on_get() -> None:
    source = (ROOT / "serve.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    handler = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "a11oy_receipt_export_v2"
    )
    handler.decorator_list = []
    sample = {
        "state": "SAMPLE",
        "data_kind": "sample",
        "operational": False,
        "receipt_minted": False,
        "signed": True,
        "payload": "e30=",
        "signatures": [{"sig": "AQ=="}],
    }

    def unexpected_signing(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("GET must not invoke a signer")

    namespace = {
        "JSONResponse": lambda payload: payload,
        "_jsonv2": json,
        "_A11OY_SAMPLE_EXPORT": sample,
        "_a11oy_sign_receipt": unexpected_signing,
    }
    module = ast.fix_missing_locations(ast.Module(body=[handler], type_ignores=[]))
    exec(compile(module, "serve.py", "exec"), namespace)
    result = asyncio.run(namespace["a11oy_receipt_export_v2"]())
    assert result == sample
    assert result is not sample


def test_console_rejects_non_sample_or_unsigned_export_before_verification() -> None:
    source = (ROOT / "console" / "index.html").read_text(encoding="utf-8")
    start = source.index("function requireSampleExport(env)")
    end = source.index("async function verifyReceipt", start)
    helper = source[start:end]
    assert source.count(
        "requireSampleExport(await getJSON(API+'/v1/receipt/export'))"
    ) == 2
    assert "Prebuilt SAMPLE envelope - signature verified in your browser" in source
    assert "does not prove an operational action" in source

    node = shutil.which("node")
    assert node is not None, "Node.js is required for the console verifier contract"
    script = """
const assert = require('node:assert/strict');
""" + helper + """
const valid = {
  state: 'SAMPLE', data_kind: 'sample', operational: false,
  receipt_minted: false, signed: true, payload: 'e30=',
  signatures: [{sig: 'AQ=='}]
};
assert.equal(requireSampleExport(valid), valid);
for (const invalid of [
  null,
  {...valid, state: 'live'},
  {...valid, operational: true},
  {...valid, receipt_minted: true},
  {...valid, signed: false},
  {...valid, payload: null},
  {...valid, signatures: []},
]) assert.throws(() => requireSampleExport(invalid));
"""
    result = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, timeout=20, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
