"""Acceptance tests for examples/verify_chain_offline.py: both keyid fingerprint
spellings, --manifest SIGNER ANCHORED / SIGNER UNKNOWN (exit 3), tamper still fails."""
import base64, hashlib, json, os, subprocess, sys
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
VERIFIER = os.environ.get("VERIFIER") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "verify_chain_offline.py")
PT = "application/vnd.szl.heart.beat+json"
def pae(t, b): return b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" " + str(len(b)).encode() + b" " + b
def cj(o): return json.dumps(o, sort_keys=True, separators=(",", ":")).encode()
def make(tmp, runtime_style=True):
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    s = pem.decode().strip().encode()
    keyid = hashlib.sha256(s if runtime_style else s + b"\n").hexdigest()   # runtime/MANIFEST vs sample convention
    beats, prev = [], "0" * 64
    for i in range(2):
        body = cj({"seq": i, "prev_beat_hash": prev, "receipt": {"action": f"a-{i}", "verdict": "ALLOW", "demo": True}, "ts": f"2026-11-12T00:00:0{i}Z"})
        sig = key.sign(pae(PT.encode(), body), ec.ECDSA(hashes.SHA256()))
        beats.append({"payloadType": PT, "payload": base64.b64encode(body).decode(), "signatures": [{"keyid": keyid, "sig": base64.b64encode(sig).decode()}]})
        prev = hashlib.sha256(pae(PT.encode(), body)).hexdigest()
    (tmp / "bundle.json").write_text(json.dumps({"payloadType": PT, "genesis": "0" * 64, "beats": beats, "expected_root": prev}))
    (tmp / "pub.pem").write_bytes(pem)
    return keyid
def run(tmp, *extra):
    return subprocess.run([sys.executable, VERIFIER, "--bundle", str(tmp / "bundle.json"), "--pubkey", str(tmp / "pub.pem"), *extra], capture_output=True, text=True)
def test_runtime_style_keyid_passes_strict(tmp_path):
    make(tmp_path, runtime_style=True)
    r = run(tmp_path, "--strict-keyid")
    assert r.returncode == 0, r.stderr
def test_sample_style_keyid_still_passes_strict(tmp_path):
    make(tmp_path, runtime_style=False)
    assert run(tmp_path, "--strict-keyid").returncode == 0
def test_unknown_signer_abstains_exit_3(tmp_path):
    make(tmp_path)
    (tmp_path / "m.json").write_text(json.dumps({"organs": {"other": {"fingerprint_sha256": "00" * 32}}}))
    r = run(tmp_path, "--manifest", str(tmp_path / "m.json"))
    assert r.returncode == 3 and "SIGNER UNKNOWN" in r.stdout
def test_listed_signer_anchored_exit_0(tmp_path):
    keyid = make(tmp_path)
    (tmp_path / "m.json").write_text(json.dumps({"organs": {"a11oy-runtime": {"fingerprint_sha256": keyid}}}))
    r = run(tmp_path, "--manifest", str(tmp_path / "m.json"), "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["signer"] == "a11oy-runtime"
def test_tamper_still_fails(tmp_path):
    make(tmp_path)
    b = json.loads((tmp_path / "bundle.json").read_text())
    p = bytearray(base64.b64decode(b["beats"][1]["payload"])); p[-2] ^= 1
    b["beats"][1]["payload"] = base64.b64encode(bytes(p)).decode()
    (tmp_path / "bundle.json").write_text(json.dumps(b))
    assert run(tmp_path).returncode == 1
