"""Acceptance tests for examples/verify_chain_offline.py key lifecycle and STALE states.

Covers: revoked keys, validity windows (not_before / not_after), unknown status
(fail closed), STALE via --max-age-days, exit-code precedence and the JSON verdict.
Bundles are generated in-test with a throwaway P-256 key; nothing is fetched.
Override the verifier under test with VERIFIER=/path/to/verify_chain_offline.py.
"""
import base64, copy, hashlib, importlib.util, json, os, subprocess, sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

HERE = Path(__file__).parent
ROOT = HERE.parent
SAMPLE = ROOT / "examples" / "offline-verify-sample"
VERIFIER = Path(os.environ.get("VERIFIER") or ROOT / "examples" / "verify_chain_offline.py").resolve()
spec = importlib.util.spec_from_file_location("vco", VERIFIER)
vco = importlib.util.module_from_spec(spec); spec.loader.exec_module(vco)

TS = ["2026-11-01T00:00:00Z", "2026-11-02T00:00:00Z", "2026-11-03T00:00:00Z"]


def make_bundle(tmp, ts=TS):
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.public_key().public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo)
    pt = "application/vnd.szl.heart.beat+json"
    running, beats = "0" * 64, []
    for i, t in enumerate(ts):
        body = vco.canonical_json({"seq": i, "prev_beat_hash": running, "ts": t,
                                   "receipt": {"action": f"test-{i}", "demo": True}})
        sig = key.sign(vco.pae(pt.encode(), body), ec.ECDSA(hashes.SHA256()))
        beats.append({"payloadType": pt, "payload": base64.b64encode(body).decode(),
                      "signatures": [{"keyid": vco.key_fingerprint(pem),
                                      "sig": base64.b64encode(sig).decode()}]})
        running = hashlib.sha256(vco.pae(pt.encode(), body)).hexdigest()
    b = {"payloadType": pt, "genesis": "0" * 64, "beats": beats, "expected_root": running}
    (tmp / "bundle.json").write_text(json.dumps(b)); (tmp / "pub.pem").write_bytes(pem)
    return pem


def manifest(tmp, pem, **fields):
    entry = {"keyid": "test-cosign", "fingerprint_sha256": vco.key_fingerprint(pem), **fields}
    (tmp / "m.json").write_text(json.dumps({"schema": "szl.khipu.cosign-keys/v1",
                                            "organs": {"testorgan": entry}}))
    return tmp / "m.json"


def run(tmp, *extra):
    p = subprocess.run([sys.executable, str(VERIFIER), "--bundle", str(tmp / "bundle.json"),
                        "--pubkey", str(tmp / "pub.pem"), "--json", *map(str, extra)],
                       capture_output=True, text=True)
    out = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {}
    return p.returncode, out


def test_committed_sample_still_passes():
    p = subprocess.run([sys.executable, str(VERIFIER), "--bundle", str(SAMPLE / "bundle.json"),
                        "--pubkey", str(SAMPLE / "pubkey.pem")], capture_output=True, text=True)
    assert p.returncode == 0 and "CHAIN OK" in p.stdout


def test_tamper_still_fails(tmp_path):
    make_bundle(tmp_path)
    b = json.loads((tmp_path / "bundle.json").read_text())
    b["beats"][1]["payload"] = base64.b64encode(b"{}").decode()
    (tmp_path / "bundle.json").write_text(json.dumps(b))
    code, out = run(tmp_path)
    assert code == 1 and out["verdict"] == "FAIL"


def test_v1_entry_without_lifecycle_is_anchored(tmp_path):
    pem = make_bundle(tmp_path)
    code, out = run(tmp_path, "--manifest", manifest(tmp_path, pem))
    assert code == 0 and out["verdict"] == "PASS" and out["signer_anchored"] is True


def test_unknown_signer_abstains(tmp_path):
    make_bundle(tmp_path)
    m = tmp_path / "m.json"; m.write_text(json.dumps({"organs": {}}))
    code, out = run(tmp_path, "--manifest", m)
    assert code == 3 and out["verdict"] == "SIGNER_UNKNOWN" and out["signer_anchored"] is False


def test_revoked_key_fails_even_for_old_beats(tmp_path):
    pem = make_bundle(tmp_path)
    code, out = run(tmp_path, "--manifest",
                    manifest(tmp_path, pem, status="revoked", revoked_at="2026-12-01T00:00:00Z"))
    assert code == 4 and out["verdict"] == "SIGNER_REVOKED" and out["signer_anchored"] is False


def test_retired_key_inside_window_passes(tmp_path):
    pem = make_bundle(tmp_path)
    code, out = run(tmp_path, "--manifest",
                    manifest(tmp_path, pem, status="retired", not_after="2026-11-10T00:00:00Z"))
    assert code == 0 and out["verdict"] == "PASS"


def test_retired_key_used_after_not_after_fails(tmp_path):
    pem = make_bundle(tmp_path)
    code, out = run(tmp_path, "--manifest",
                    manifest(tmp_path, pem, status="retired", not_after="2026-11-02T12:00:00Z"))
    assert code == 4 and out["verdict"] == "SIGNER_NOT_VALID_AT_TIME"


def test_retired_without_not_after_fails_closed(tmp_path):
    pem = make_bundle(tmp_path)
    code, out = run(tmp_path, "--manifest", manifest(tmp_path, pem, status="retired"))
    assert code == 4


def test_beat_before_not_before_fails(tmp_path):
    pem = make_bundle(tmp_path)
    code, out = run(tmp_path, "--manifest",
                    manifest(tmp_path, pem, not_before="2026-11-02T00:00:01Z"))
    assert code == 4 and out["verdict"] == "SIGNER_NOT_VALID_AT_TIME"


def test_unrecognized_status_fails_closed(tmp_path):
    pem = make_bundle(tmp_path)
    code, out = run(tmp_path, "--manifest", manifest(tmp_path, pem, status="probably-fine"))
    assert code == 4


def test_stale_bundle_abstains(tmp_path):
    pem = make_bundle(tmp_path)
    code, out = run(tmp_path, "--manifest", manifest(tmp_path, pem),
                    "--max-age-days", "30", "--now", "2027-01-15T00:00:00Z")
    assert code == 5 and out["verdict"] == "STALE" and out["signer_anchored"] is True


def test_fresh_bundle_not_stale(tmp_path):
    make_bundle(tmp_path)
    code, out = run(tmp_path, "--max-age-days", "30", "--now", "2026-11-10T00:00:00Z")
    assert code == 0 and out["verdict"] == "PASS"


def test_precedence_unknown_beats_stale(tmp_path):
    make_bundle(tmp_path)
    m = tmp_path / "m.json"; m.write_text(json.dumps({"organs": {}}))
    code, out = run(tmp_path, "--manifest", m, "--max-age-days", "1", "--now", "2027-01-01T00:00:00Z")
    assert code == 3


def test_unparseable_timestamp_fails_closed(tmp_path):
    make_bundle(tmp_path, ts=["yesterday", "2026-11-02T00:00:00Z", "2026-11-03T00:00:00Z"])
    code, out = run(tmp_path, "--max-age-days", "30")
    assert code == 1 and out["verdict"] == "FAIL"



def test_intermediate_timestamp_outside_window_fails(tmp_path):
    # Both endpoints are within the manifest window; a signed middle beat
    # outside it must never be accepted through endpoint-only validation.
    pem = make_bundle(tmp_path, ts=[
        "2026-11-01T00:00:00Z", "2026-11-20T00:00:00Z",
        "2026-11-03T00:00:00Z"])
    code, out = run(tmp_path, "--manifest",
                    manifest(tmp_path, pem, not_after="2026-11-10T00:00:00Z"))
    assert code == 1 and out["verdict"] == "FAIL"


def test_intermediate_timestamp_malformed_without_freshness_fails(tmp_path):
    make_bundle(tmp_path, ts=[
        "2026-11-01T00:00:00Z", "not-a-timestamp",
        "2026-11-03T00:00:00Z"])
    code, out = run(tmp_path)
    assert code == 1 and out["verdict"] == "FAIL"


def test_out_of_order_signed_beats_fail_without_manifest(tmp_path):
    make_bundle(tmp_path, ts=[
        "2026-11-03T00:00:00Z", "2026-11-02T00:00:00Z",
        "2026-11-04T00:00:00Z"])
    code, out = run(tmp_path)
    assert code == 1 and out["verdict"] == "FAIL"


def test_malformed_manifest_time_is_usage_error(tmp_path):
    pem = make_bundle(tmp_path)
    code, out = run(tmp_path, "--manifest",
                    manifest(tmp_path, pem, not_before="invalid-date"))
    assert code == 2 and out["verdict"] == "USAGE" and out["exit_code"] == 2


def test_malformed_now_is_usage_error(tmp_path):
    make_bundle(tmp_path)
    code, out = run(tmp_path, "--max-age-days", "30", "--now", "not-a-date")
    assert code == 2 and out["verdict"] == "USAGE"


@pytest.mark.parametrize("age", ["NaN", "Infinity", "-1"])
def test_invalid_staleness_limit_is_usage_error(tmp_path, age):
    make_bundle(tmp_path)
    code, out = run(tmp_path, "--max-age-days", age)
    assert code == 2 and out["verdict"] == "USAGE"


def test_equal_timestamp_signed_beats_remain_compatible(tmp_path):
    make_bundle(tmp_path, ts=[
        "2026-11-03T00:00:00Z", "2026-11-03T00:00:00Z",
        "2026-11-03T00:00:00Z"])
    code, out = run(tmp_path)
    assert code == 0 and out["verdict"] == "PASS"
