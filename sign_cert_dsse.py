#!/usr/bin/env python3
# Real Ed25519 DSSE-PAE signature over the MEASURED certificate. No fabrication:
# signs with /root/ed25519.pem via openssl and self-verifies before writing.
#
# conformant-to: DSSE-v1 spec ASCII-decimal PAE (cosign verify-blob family).
# NOT importing szl-receipt (reason: szl-receipt uses a NON-standard struct-packed
# little-endian PAE + ECDSA-P256; this signer is Ed25519 + ASCII-decimal PAE, so
# delegating would change the signed bytes and break existing verification). The
# byte divergence is locked by tests/test_sign_cert_dsse_parity.py — see
# RECEIPT_BUS_EXEC.md before changing pae() or PAYLOAD_TYPE.
import json, base64, subprocess, os, hashlib, sys

KEY = "/root/ed25519.pem"; D = "/opt/szl/a11oy"
CERT = os.path.join(D, "physical_bounds_certificate.json")
PT = "application/vnd.szl.physical-bounds-certificate+json"
PAYLOAD_TYPE = PT  # importable alias for conformance tests


def pae(t, b):
    t = t.encode()
    return b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" " + str(len(b)).encode() + b" " + b


def main():
    body = open(CERT, "rb").read()
    P = pae(PT, body)
    open("/tmp/pae.bin", "wb").write(P)
    subprocess.run(["openssl", "pkey", "-in", KEY, "-pubout", "-out", "/tmp/pub.pem"], check=True)
    subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", KEY, "-rawin", "-in", "/tmp/pae.bin", "-out", "/tmp/sig.bin"], check=True)
    v = subprocess.run(["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", "/tmp/pub.pem", "-rawin", "-in", "/tmp/pae.bin", "-sigfile", "/tmp/sig.bin"], capture_output=True, text=True)
    if "Signature Verified Successfully" not in (v.stdout + v.stderr):
        print("ABORT: signature did not verify:", v.stdout, v.stderr, file=sys.stderr); sys.exit(3)
    sig = open("/tmp/sig.bin", "rb").read(); pub = open("/tmp/pub.pem", "rb").read()
    keyid = "sha256:" + hashlib.sha256(pub).hexdigest()
    env = {"payloadType": PT, "payload": base64.b64encode(body).decode(),
           "signatures": [{"keyid": keyid, "sig": base64.b64encode(sig).decode(), "publicKey": pub.decode()}],
           "_dsse": "DSSEv1 PAE, alg=ed25519 (real key), self-verified with openssl",
           "_cert_sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
           "_transparency_note": "Real cryptographic DSSE signature. Public transparency-log anchoring (governance-receipts / Sigstore keyless) is the CI/FA-001 path; this is the on-metal Ed25519 attestation."}
    out = os.path.join(D, "physical_bounds_certificate.dsse.json")
    open(out, "w").write(json.dumps(env, indent=2))
    for f in ("/tmp/pae.bin", "/tmp/sig.bin"):
        try: os.remove(f)
        except: pass
    print("DSSE SIGNED + SELF-VERIFIED ->", out)
    print("keyid", keyid, "cert_sha256", "sha256:" + hashlib.sha256(body).hexdigest())


if __name__ == "__main__":
    main()
