#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Adversarial checks for the bounded offline receipt-observation profile."""

import copy
import hashlib
import json
import socket

import pytest

from scripts.import_evidence_receipts import import_manifest, main
from szl_evidence_receipts import (
    MAX_BUNDLE_BYTES, MAX_BUNDLE_EDGES, MAX_RECEIPT_BYTES,
    build_bundle, decode_bundle, import_receipt,
)

URI = "https://huggingface.co/datasets/SZLHOLDINGS/fixture/resolve/" + "a" * 40 + "/receipt.json"
AT = "2026-11-16T22:57:52Z"
RAW = b'{"schema":"szl.fixture/v1","verdict":"ok","base":"SZLHOLDINGS/fixture-base","adapter_repo":"SZLHOLDINGS/fixture-adapter"}'


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def edge(raw=RAW, **kwargs):
    options = {
        "expected_sha256": hashlib.sha256(raw).hexdigest(),
        "artifact_uri": URI, "kind": "evaluation", "observed_at": AT,
    }
    options.update(kwargs)
    return import_receipt(raw, **options)


def rehash(bundle):
    unsigned = {key: bundle[key] for key in ("schema", "signature_status", "edges")}
    bundle["digest_sha256"] = hashlib.sha256(encoded(unsigned)).hexdigest()
    return bundle


def test_receipt_observation_is_deterministic_and_not_authority(monkeypatch):
    def deny_network(*args, **kwargs):
        pytest.fail("offline import attempted network access")
    monkeypatch.setattr(socket, "socket", deny_network)
    first, second = edge(), edge()
    assert first.as_dict() == second.as_dict()
    assert first.source_revision is None
    assert first.verdict == "OBSERVED"
    assert first.authority["execution_authorized"] is False
    assert first.evidence["claims_verified"] is False
    assert first.evidence["signature_status"] == "UNVERIFIED"
    assert first.evidence["reported_verdict"] == "ok"
    assert first.evidence["reported_base"] == "SZLHOLDINGS/fixture-base"
    assert first.evidence["artifact_uri"] == URI
    assert first.artifact_sha256 == hashlib.sha256(RAW).hexdigest()


def test_reported_kind_is_an_unverified_label():
    result = edge(b'{"kind":"szl.salad-worker/v1"}', kind="training")
    assert result.evidence["reported_kind"] == "szl.salad-worker/v1"
    assert result.verdict == "OBSERVED"
    assert result.evidence["claims_verified"] is False


def test_private_fields_prompts_outputs_and_signature_are_stripped():
    receipt = {
        "schema": "szl.fixture/v1", "verdict": "VERIFIED",
        "prompt": "SENSITIVE PROMPT", "output": "SENSITIVE OUTPUT",
        "token": "SENSITIVE CREDENTIAL", "signature": "UNVERIFIED BYTES",
        "private_key": "SENSITIVE KEY", "source_revision": "b" * 40,
        "adapter_results": [{"output": "SENSITIVE NESTED OUTPUT"}],
        "model": {"name": "SENSITIVE MODEL OBJECT"},
        "adapter_repo": "hf_fixturecredential",
        "base": "contains whitespace and private text",
    }
    result = edge(encoded(receipt))
    public = encoded(result.as_dict()).decode()
    assert "SENSITIVE" not in public
    assert "UNVERIFIED BYTES" not in public
    assert "hf_fixturecredential" not in public
    assert "reported_adapter" not in result.evidence
    assert "reported_base" not in result.evidence
    assert result.source_revision is None
    assert result.evidence["reported_verdict"] == "VERIFIED"
    assert result.verdict == "OBSERVED"


@pytest.mark.parametrize("identifier", ["https://example.invalid/secret", "../private", "owner/model/extra", "owner/sk-fixture", "contains spaces"])
def test_model_identifiers_cannot_be_arbitrary_text_or_paths(identifier):
    result = edge(encoded({"model": identifier}))
    assert "reported_model" not in result.evidence


def test_digest_mismatch_is_checked_before_parsing():
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        edge(b"not JSON", expected_sha256="0" * 64)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        edge(RAW + b" ", expected_sha256=hashlib.sha256(RAW).hexdigest())


@pytest.mark.parametrize("raw", [
    b'{"schema":"a","schema":"b"}', b'{"nested":{"a":1,"a":2}}',
    b'{"value":NaN}', b'{"value":Infinity}', b'{"value":-Infinity}',
    b'{"value":1e999}', b'[]', b'null', b'\xff', b'{"broken":',
    b'{"x":' * 34 + b'0' + b'}' * 34,
])
def test_invalid_json_is_rejected(raw):
    with pytest.raises(ValueError):
        edge(raw)


@pytest.mark.parametrize("uri", [
    URI.replace("https://", "http://"),
    URI.replace("huggingface.co", "huggingface.co.evil.invalid"),
    URI.replace("huggingface.co", "user:password@huggingface.co"),
    URI.replace("huggingface.co", "huggingface.co:443"),
    URI.replace("a" * 40, "main"), URI.replace("a" * 40, "A" * 40),
    URI + "?token=credential", URI + "#fragment", URI + "?", URI + "#",
    URI.replace("receipt.json", "../receipt.json"),
    URI.replace("receipt.json", "%2e%2e/receipt.json"),
    URI.replace("/resolve/", "/blob/"), URI.replace("/datasets/", "/spaces/"),
    "file:///tmp/receipt.json", URI + "\n",
])
def test_only_immutable_hf_resolve_urls_are_accepted(uri):
    with pytest.raises(ValueError):
        edge(artifact_uri=uri)


def test_model_resolve_url_and_timezone_are_supported():
    model_uri = URI.replace("/datasets/", "/")
    result = edge(artifact_uri=model_uri, observed_at="2026-11-16T17:57:52-05:00")
    assert result.evidence["observed_at"] == AT
    assert result.evidence["artifact_uri"] == model_uri


@pytest.mark.parametrize("options", [
    {"kind": "deployment"}, {"kind": ["evaluation"]}, {"expected_sha256": "xyz"},
    {"observed_at": "2026-11-16"}, {"observed_at": "2026-11-16T22:00:00"},
    {"observed_at": "2026-02-30T22:00:00Z"},
    {"observed_at": "0001-01-01T00:00:00+01:00"},
    {"observed_at": "9999-12-31T23:59:59-01:00"},
])
def test_invalid_import_arguments_are_rejected(options):
    with pytest.raises(ValueError):
        edge(**options)


def test_bounds_are_enforced_before_unbounded_work():
    with pytest.raises(ValueError):
        edge(b"x" * (MAX_RECEIPT_BYTES + 1))
    with pytest.raises(ValueError):
        decode_bundle(b"x" * (MAX_BUNDLE_BYTES + 1))
    with pytest.raises(ValueError):
        build_bundle(edge() for _ in range(MAX_BUNDLE_EDGES + 1))
    excessive = rehash({
        "schema": "szl.evidence-bundle/v1", "signature_status": "UNSIGNED",
        "edges": [edge().as_dict()] * (MAX_BUNDLE_EDGES + 1),
    })
    with pytest.raises(ValueError):
        decode_bundle(encoded(excessive))


def test_bundle_is_unsigned_order_independent_and_deduplicated():
    evaluation, training = edge(), edge(kind="training")
    bundle = build_bundle([evaluation, training, evaluation])
    assert bundle == build_bundle([training, evaluation])
    assert bundle["signature_status"] == "UNSIGNED"
    assert len(bundle["edges"]) == 2
    decoded = decode_bundle(encoded(bundle))
    assert [item.as_dict() for item in decoded] == bundle["edges"]
    assert build_bundle(decoded) == bundle


def test_bundle_digest_and_edge_ids_are_both_checked():
    bundle = build_bundle([edge()])
    corrupt = copy.deepcopy(bundle)
    corrupt["edges"][0]["evidence"]["reported_verdict"] = "fail"
    with pytest.raises(ValueError, match="digest mismatch"):
        decode_bundle(encoded(corrupt))
    rehash(corrupt)
    with pytest.raises(ValueError, match="receipt_id"):
        decode_bundle(encoded(corrupt))
    duplicate_key = encoded(bundle)[:-1] + b',"signature_status":"UNSIGNED"}'
    with pytest.raises(ValueError, match="duplicate"):
        decode_bundle(duplicate_key)


@pytest.mark.parametrize("field,value", [
    ("verdict", "VERIFIED"), ("source_revision", "c" * 40),
    ("runtime", {"revision": "d" * 40}), ("parents", ["edge-" + "e" * 64]),
    ("authority", {"execution_authorized": True, "method": "offline-receipt-byte-match"}),
])
def test_rehashed_bundle_cannot_upgrade_observation(field, value):
    bundle = build_bundle([edge()])
    bundle["edges"][0][field] = value
    with pytest.raises(ValueError):
        decode_bundle(encoded(rehash(bundle)))


def test_rehashed_bundle_cannot_publish_arbitrary_fields():
    bundle = build_bundle([edge()])
    bundle["edges"][0]["evidence"]["output"] = "PRIVATE OUTPUT"
    with pytest.raises(ValueError, match="unsupported fields"):
        decode_bundle(encoded(rehash(bundle)))
    bundle = build_bundle([edge()])
    bundle["signature_status"] = "SIGNED"
    with pytest.raises(ValueError):
        decode_bundle(encoded(rehash(bundle)))


def manifest(tmp_path, raw=RAW):
    (tmp_path / "receipt.json").write_bytes(raw)
    value = {
        "schema": "szl.evidence-import-manifest/v1",
        "receipts": [{
            "path": "receipt.json", "expected_sha256": hashlib.sha256(raw).hexdigest(),
            "artifact_uri": URI, "kind": "evaluation", "observed_at": AT,
        }],
    }
    path = tmp_path / "manifest.json"
    path.write_bytes(encoded(value))
    return path, value


def test_cli_atomic_output_and_rejected_input_preserve_prior_bundle(tmp_path):
    path, value = manifest(tmp_path)
    output = tmp_path / "bundle.json"
    imported = import_manifest(path, output)
    before = output.read_bytes()
    assert decode_bundle(before)[0].as_dict() == imported["edges"][0]
    assert not list(tmp_path.glob(".receipt-bundle-*"))
    value["receipts"][0]["expected_sha256"] = "0" * 64
    path.write_bytes(encoded(value))
    assert main(["--manifest", str(path), "--output", str(output)]) == 2
    assert output.read_bytes() == before
    assert not list(tmp_path.glob(".receipt-bundle-*"))


def test_cli_will_not_replace_inputs_or_read_network_paths(tmp_path):
    path, value = manifest(tmp_path)
    with pytest.raises(ValueError, match="must not replace"):
        import_manifest(path, tmp_path / "receipt.json")
    value["receipts"][0]["path"] = "//remote/share/receipt.json"
    path.write_bytes(encoded(value))
    with pytest.raises(ValueError, match="local file"):
        import_manifest(path, tmp_path / "bundle.json")


@pytest.mark.parametrize("parameter", ["manifest_path", "output_path"])
@pytest.mark.parametrize("network_path", [r"\\server\share\receipt.json", "//server/share/receipt.json"])
def test_explicit_network_manifest_and_output_reject_before_file_access(monkeypatch, parameter, network_path):
    def deny_filesystem(*args, **kwargs):
        pytest.fail("explicit network path reached filesystem access")
    monkeypatch.setattr("scripts.import_evidence_receipts._read", deny_filesystem)
    monkeypatch.setattr("scripts.import_evidence_receipts.Path.resolve", deny_filesystem)
    arguments = {"manifest_path": "manifest.json", "output_path": "bundle.json"}
    arguments[parameter] = network_path
    with pytest.raises(ValueError, match="local file"):
        import_manifest(**arguments)
