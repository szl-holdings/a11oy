# SIGNED_SELF_AUDIT — the play no funded competitor can copy

SZL Holdings / a11oy payload 05. Binding source of truth: `../CANON.md`.

This directory ships two artifacts and one claim:

- `a11oy_verify.py` — a single-file, stdlib-only verifier. Anyone with a bare
  `python3` (no pip, no network, no vendor) can check any a11oy receipt bundle.
- `tools/make_self_audit.py` — a stdlib-only generator that audits SZL's **own**
  estate and emits a `szl.dev/GovernedAction/v1` receipt for that audit with
  `completeness: INCOMPLETE`, `side_effect_class: READ_ONLY`, a populated
  `limitations[]` array, and a real Ed25519 DSSE signature (or an honestly
  recorded `SIGNATURE_DEFERRED` — never a fake one).
- The claim: **publishing a signed, offline-verifiable audit receipt that
  openly says INCOMPLETE about yourself is the lightning-strike demo.**

## Why this is the demo

The competitive map (CANON section 5) is unambiguous: the
monitor/control/police lane is capitalized roughly 10x beyond reach. Zenity,
Obsidian, WitnessAI and the rest sell consoles that render their customers'
estates as green. The lane that is actually open is **whose receipt format an
independent auditor trusts after the vendor is gone**. Trust in a receipt
format is not established by saying the format is honest. It is established by
the vendor publishing a receipt the vendor would rather not publish — and
making it checkable without the vendor.

The receipt in `scratch/self_audit_bundle.json` does three things at once:

1. **The signature proves the artifact was not altered.** Ed25519 over the
   exact DSSE PAE (`b'DSSE'` + BE-length-prefixed payload type + payload), over
   the canonical JSON of the receipt, hash-committed. Flip one byte and
   `a11oy_verify.py` returns FAIL (exit 1).
2. **The content proves the artifact was not flattered.** The receipt says
   `completeness: INCOMPLETE` and lists eight limitations, including that 45
   Spaces exist against 26 previously advertised, that 29 Docker/Gradio Spaces
   ride a team plan with unconfirmed billing exposure, and that 17 Spaces were
   created in one ungoverned 48-hour burst. Signature is not truth
   (CANON Law 5); here integrity and candor are demonstrated as separate
   properties, on the same artifact, about the vendor itself.
3. **The verifier proves no trust in SZL is required.** One file, stdlib-only,
   real exit codes. If the `cryptography` package is absent, the signature
   check reports `SIGNATURE_UNVERIFIED_NO_CRYPTO` and the verdict degrades to
   INCOMPLETE — the verifier never reports PASS on a signature it did not
   verify. The buyer's 5-minute test (CANON section 4) works against this
   exact artifact: download, disconnect, verify, alter a byte (watch FAIL),
   inspect the limitations.

A funded competitor can copy the words on this page in an afternoon. What it
cannot copy is the posture, because the posture is only available to a vendor
whose tooling actually enforces it: if SZL's own tooling cannot be made to say
PASS over SZL's own unaudited gaps, then no customer's receipt can be rounded
up either. A dashboard vendor publishing "INCOMPLETE" about itself would be
admitting its green checkmarks round up. That is why the play does not
transfer.

This is the Zero-Bandaid Law (CANON Law 1) applied to marketing: the
strongest evidence that the evidence model works is the vendor refusing to
round its own gaps up, in a signed, portable, offline-checkable form.

## What the receipt records

| Field | Value | Why |
|---|---|---|
| `predicate_type` | `szl.dev/GovernedAction/v1` | the proprietary predicate (CANON section 2) |
| `action_type` | `estate.self_audit` | the audit of SZL's own estate |
| `side_effect_class` | `READ_ONLY` | the audit only reads (Law 6) |
| `completeness` | `INCOMPLETE` | Law 4: missing evidence never passes |
| `limitations[]` | 8 entries | every known gap, disclosed on the receipt |
| `actor.is_service_account` | `false` | Law 3: a natural person is accountable |
| `rfc3161_token` / `ntp_synced` | `UNAVAILABLE` / `false` | honest time: recorded, strength judged weak |
| `retention_days` | `180` | Law 10 floor |
| signature | `ed25519-dsse` or `SIGNATURE_DEFERRED` | never faked |

## Regenerate it: the exact 5 commands

From this directory (`payloads/05-verifier/`):

```sh
# 1. Prove the verifier catches all six tamper classes (writes test_vectors/).
python3 a11oy_verify.py --self-test
#    expected: SELF-TEST PASS: 8/8 cases produced the expected verdict — exit 0

# 2. Regenerate the self-audit receipt (runs the master demo harness as evidence,
#    hashes the Spaces-audit outputs and the reconciled inventory, signs).
python3 tools/make_self_audit.py --out scratch
#    expected: exit 0; signature scheme ed25519-dsse (or SIGNATURE_DEFERRED
#    on a host without the cryptography package — stated on the receipt)

# 3. Offline-verify the audit receipt. INCOMPLETE is the expected, honest verdict.
python3 a11oy_verify.py scratch/self_audit_bundle.json
#    expected: FINAL: INCOMPLETE — exit 2

# 4. Demonstrate the no-crypto honesty path on a bare interpreter (no site-packages).
python3 -S tools/make_self_audit.py --out scratch/deferred
#    expected: exit 0; signature scheme: SIGNATURE_DEFERRED, reason recorded

# 5. Verify the deferred bundle: signature counted unverified, never assumed.
python3 -S a11oy_verify.py scratch/deferred/self_audit_bundle.json
#    expected: FINAL: INCOMPLETE — exit 2
```

Observed at build time (2026-08-30, Python 3.14.3, cryptography 50.0.1):
commands 1–5 exited 0, 0, 2, 0, 2 respectively. See `scratch/VALIDATION_LOG.txt`
for the full recorded run.

## Exit-code contract of `a11oy_verify.py`

| Exit | Verdict | Meaning |
|---|---|---|
| 0 | PASS | every check passed; signature actually verified |
| 1 | FAIL | structural violation, Law 3 breach, hash/signature/chain/redaction mismatch |
| 2 | INCOMPLETE | missing evidence, declared INCOMPLETE, weak time, unsigned/unverifiable signature, undisclosed redaction |
| 3 | — | usage or IO error (not a verdict) |

## The six tamper classes the verifier catches (test_vectors/)

| Vector | Attack | Verdict | Exit |
|---|---|---|---|
| `valid.json` | none (single signed receipt) | PASS | 0 |
| `tampered_byte_flip.json` | one byte changed, hash/signature stale | FAIL | 1 |
| `tampered_evidence_removal.json` | evidence stripped, re-hashed honestly | INCOMPLETE | 2 |
| `tampered_service_account.json` | `is_service_account: true` (Law 3) | FAIL | 1 |
| `tampered_sequence_gap.json` | middle receipt removed from a 3-chain | FAIL | 1 |
| `tampered_redaction_cheat.json` | substituted plaintext under a commitment | FAIL | 1 |
| `tampered_weak_time.json` | TSA token UNAVAILABLE, NTP unsynced | INCOMPLETE | 2 |
| `valid_chain.json` | none (three-receipt hash-linked chain) | PASS | 0 |

On a host without `cryptography`, the two signed valid bundles degrade to
INCOMPLETE (exit 2) with `SIGNATURE_UNVERIFIED_NO_CRYPTO` printed — never to a
wrong PASS. Every tamper verdict is unchanged.

## Relationship to the production signing path

CANON section 2: production signing uses the maintained `in-toto-attestation`
PyPI package plus `securesystemslib` (Ed25519 DSSE); do not hand-roll DSSE/PAE
in production code. `make_self_audit.py` is not production signing code — it
is the reference implementation of the *verification* side, which is the side
an auditor runs. Its pre-authentication encoding is exactly the one this
payload specifies (`b'DSSE'` + 4-byte big-endian length of the payload type +
payload type + 4-byte big-endian length of the payload + payload), and it is
implemented here for verification only; envelopes signed by the production
path are verified by the same check. Note this framing differs from the
upstream DSSEv1 text encoding (which uses a `DSSEv1` tag and decimal ASCII
lengths): the a11oy bundle format fixes the binary framing above so a
verifier needs no DSSE library, and the difference is stated here rather than
glossed. When `cryptography` is unavailable the generator says
`SIGNATURE_DEFERRED` with the reason, on the receipt, in the open.
