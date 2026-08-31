"""S2.6 — Enumerate every way the verifier could be made to output a
passing verdict on a tampered or incomplete bundle, and prove each fails.

Executed against the real merged code (src/a11oy/, commit post-#1534).
A PASS here means the ATTACK FAILED (verifier held). Any test that cannot
be made to pass documents a live finding in docs/security/.
"""

from __future__ import annotations

import base64
import copy
import json

from a11oy.schemas import RedactionCommitment
from a11oy.signing import DemoEd25519Backend

from .conftest import SECRET_PLAINTEXT, SALT, build_valid_receipt, decode_payload, reencode_payload


def _passing(result) -> bool:
    # A "passing" verdict an auditor would accept: signature valid AND claim
    # not FAIL/INCOMPLETE.
    return result.signature_valid and result.verdict == "VALID"


def test_baseline_valid_envelope_passes(signed_envelope):
    r = signed_envelope["verifier"].verify_envelope(
        signed_envelope["envelope"], required_obligations=("test_log",)
    )
    assert r.signature_valid, r.problems
    assert r.verdict == "VALID", r.problems


def test_attack_1_one_byte_tamper(signed_envelope):
    """Flip one byte inside the base64 payload, keep the signature."""
    env = copy.deepcopy(signed_envelope["envelope"])
    raw = bytearray(base64.b64decode(env["payload"]))
    raw[len(raw) // 2] ^= 0x01
    env["payload"] = base64.b64encode(bytes(raw)).decode("ascii")
    r = signed_envelope["verifier"].verify_envelope(env)
    assert not _passing(r), "one-byte tamper produced a passing verdict"


def test_attack_2_completeness_flag_flip_unsigned(signed_envelope):
    """Attacker takes a genuinely INCOMPLETE receipt, flips the flag to
    COMPLETE in the payload, keeps the original signature."""
    receipt_dict, _ = build_valid_receipt()
    receipt_dict["predicate"]["completeness"] = "INCOMPLETE"  # evidence still present
    b = DemoEd25519Backend()
    env = b.sign(receipt_dict)
    verifier = signed_envelope["verifier"].__class__({b.keyid: b.public_key_raw})
    r0 = verifier.verify_envelope(env)
    assert r0.verdict == "INCOMPLETE"  # baseline: honestly flagged
    tampered = decode_payload(env)
    tampered["predicate"]["completeness"] = "COMPLETE"
    env2 = reencode_payload(env, tampered)
    r = verifier.verify_envelope(env2)
    assert not _passing(r), "flag flip without re-sign passed"


def test_attack_3_law3_service_account_spoof_unsigned(signed_envelope):
    """S2.8: set is_service_account=true, claim a bot acted, no re-sign."""
    receipt = decode_payload(signed_envelope["envelope"])
    receipt["predicate"]["actor"]["is_service_account"] = True
    env = reencode_payload(signed_envelope["envelope"], receipt)
    r = signed_envelope["verifier"].verify_envelope(env)
    assert not _passing(r), "service-account spoof passed"
    assert r.claim_state.value == "FAIL"


def test_attack_4_strip_evidence_keep_flag_unsigned(signed_envelope):
    """Remove all evidence but keep completeness=COMPLETE, no re-sign."""
    receipt = decode_payload(signed_envelope["envelope"])
    receipt["predicate"]["evidence"] = []
    env = reencode_payload(signed_envelope["envelope"], receipt)
    r = signed_envelope["verifier"].verify_envelope(env)
    assert not _passing(r), "evidence strip passed"


def test_attack_5_redaction_salt_tamper(signed_envelope):
    """S2.7: commitments are inside the signed payload, so flipping a salt
    byte without re-signing must fail signature verification."""
    receipt = decode_payload(signed_envelope["envelope"])
    rc = receipt["predicate"]["redaction_commitments"][0]
    salt = bytearray(base64.b64decode(rc["salt_b64"]))
    salt[0] ^= 0xFF
    rc["salt_b64"] = base64.b64encode(bytes(salt)).decode("ascii")
    env = reencode_payload(signed_envelope["envelope"], receipt)
    r = signed_envelope["verifier"].verify_envelope(env)
    assert not _passing(r), "salt tamper without re-sign passed"
    # And the commitment itself must no longer verify the plaintext.
    tampered = RedactionCommitment(**rc)
    assert not tampered.verify(SECRET_PLAINTEXT)


def test_attack_6_sign_then_strip_issuer_side(signed_envelope):
    """THE TRANSCRIPT-MUTATION VECTOR: the signer re-signs a redacted copy.

    If the issuer signs, then redacts evidence and RE-SIGNS the stripped
    receipt with the same key (or the platform does it on their behalf),
    does anything detect the change? This is the vector that needs an
    out-of-band anchor (flight-recorder chain head / witnessed digest).
    """
    # Sign the ORIGINAL with a fresh backend to model the issuer's own
    # flow, then sign the STRIPPED copy with the same key.
    b = DemoEd25519Backend()
    receipt = signed_envelope["receipt_dict"]
    env_original = b.sign(receipt)

    stripped = copy.deepcopy(receipt)
    stripped["predicate"]["evidence"] = []
    stripped["predicate"]["completeness"] = "INCOMPLETE"  # honest re-sign
    env_stripped = b.sign(stripped)

    verifier = signed_envelope["verifier"].__class__({b.keyid: b.public_key_raw})
    r_orig = verifier.verify_envelope(env_original)
    r_strip = verifier.verify_envelope(env_stripped)

    # Both verify — signature-wise the stripped copy is equally "valid".
    assert r_orig.signature_valid and r_strip.signature_valid
    # What saves the claim layer: the honest re-sign must DOWNGRADE, and it
    # does (INCOMPLETE, never PASS). Documented invariant:
    assert r_strip.verdict == "INCOMPLETE"

    # S2.6-6 regression (fixed 2026-08-31): a PARTIAL strip (evidence list
    # stays non-empty) re-signed as COMPLETE previously verified VALID when
    # the caller passed no obligations. The verifier now falls back to the
    # receipt-carried obligations, so the stripped bundle can no longer pass.
    partial = copy.deepcopy(receipt)
    partial["predicate"]["evidence"] = partial["predicate"]["evidence"][:1]
    r_partial = verifier.verify_envelope(b.sign(partial))  # no obligations passed
    assert r_partial.verdict == "INCOMPLETE", (
        "S2.6-6 REGRESSED: partial strip with issuer re-sign passed again"
    )
    assert any("missing evidence obligations" in p for p in r_partial.problems)
    # RESIDUAL GAP (recorded in docs/security/ADVERSARIAL_REVIEW...): if the
    # issuer re-signs a stripped copy AND keeps completeness=COMPLETE, the
    # schema validator (Law 4 model validator) still rejects it at verify
    # time — check_claims re-validates the schema:
    dishonest = copy.deepcopy(receipt)
    dishonest["predicate"]["evidence"] = []
    dishonest["predicate"]["completeness"] = "COMPLETE"
    r_dishonest = verifier.verify_envelope(b.sign(dishonest))
    assert r_dishonest.verdict != "VALID", (
        "LIVE FINDING: issuer-signed stripped receipt with COMPLETE flag "
        "produced VALID"
    )
    assert r_dishonest.claim_state.value == "FAIL"


def test_attack_7_deny_to_allow_flip_unsigned(signed_envelope):
    """Rewrite decision DENY->ALLOW post-hoc without the key."""
    receipt = decode_payload(signed_envelope["envelope"])
    receipt["decision"]["decision"] = "DENY"
    # First make a DENY receipt that is otherwise valid...
    env_deny = reencode_payload(signed_envelope["envelope"], receipt)
    r1 = signed_envelope["verifier"].verify_envelope(env_deny)
    assert not _passing(r1)  # unsigned edit fails signature
    # ...and flipping back is equally caught:
    receipt2 = decode_payload(signed_envelope["envelope"])
    receipt2["decision"]["decision"] = "ALLOW"
    receipt2["decision"]["reason"] = "attacker-wrote-this"
    env_allow = reencode_payload(signed_envelope["envelope"], receipt2)
    r2 = signed_envelope["verifier"].verify_envelope(env_allow)
    assert not _passing(r2)


def test_attack_8_keyid_substitution(signed_envelope):
    """Point the envelope at a DIFFERENT registered keyid."""
    other = __import__("a11oy.signing", fromlist=["DemoEd25519Backend"]).DemoEd25519Backend()
    verifier = signed_envelope["verifier"].__class__(
        {**signed_envelope["verifier"]._public_keys, other.keyid: other.public_key_raw}
    )
    env = copy.deepcopy(signed_envelope["envelope"])
    env["signatures"][0]["keyid"] = other.keyid
    r = verifier.verify_envelope(env)
    assert not _passing(r), "keyid substitution passed"


def test_attack_9_double_signature(signed_envelope):
    """Append a second attacker signature to the envelope."""
    env = copy.deepcopy(signed_envelope["envelope"])
    env["signatures"].append({"keyid": "attacker", "sig": env["signatures"][0]["sig"]})
    r = signed_envelope["verifier"].verify_envelope(env)
    assert not _passing(r), "double-signature envelope passed"
