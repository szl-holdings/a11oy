# Adversarial Review — a11oy Governed Slice
**Date:** 2026-08-31 · **Scope:** authorized defensive review of first-party code
(`src/a11oy/{verifier,signing,policy,flight_recorder,schemas}.py`, commit post-#1534)
· **Method:** 23 executable attack tests in `tests/adversarial/`, all run against the
merged code. **Result: 23/23 attack defenses held; 1 residual finding (S2.6-6); 1
harness defect found and fixed (demo step 9).**

## S2.6 — Ways a verifier could be made to output PASS on a tampered/incomplete bundle

| # | Attack vector | Result |
|---|---|---|
| 1 | One-byte tamper in signed payload (no re-sign) | **HELD** — INVALID, signature fails |
| 2 | Flip `completeness: INCOMPLETE→COMPLETE`, keep signature | **HELD** — INVALID |
| 3 | Law 3 spoof: `is_service_account: true` in payload, no re-sign | **HELD** — claim FAIL |
| 4 | Strip all evidence, keep `COMPLETE`, no re-sign | **HELD** — INVALID |
| 5 | Tamper redaction-commitment salt byte, no re-sign | **HELD** — INVALID + commitment no longer verifies plaintext |
| 6 | **Issuer-side sign-then-strip: re-sign a redacted copy with the same key** | **RESIDUAL FINDING — see below** |
| 7 | Rewrite decision DENY→ALLOW post-hoc | **HELD** — INVALID |
| 8 | keyid substitution against a different registered key | **HELD** — INVALID |
| 9 | Append a second attacker signature | **HELD** — rejected (demo envelope carries exactly one) |

### Finding S2.6-6 (MEDIUM) — **FIXED 2026-08-31, regression-tested**: partial-evidence-strip with issuer re-sign
If the party holding the signing key strips **some** evidence items (keeping the list
non-empty), re-signs with `completeness: COMPLETE`, and the verifier is invoked
**without** the policy-declared `required_obligations`, the bundle verifies as VALID
(observed: `verdict=VALID, claim=PASS, problems=[]`).

**Why the architecture still catches it in the intended flow:** the obligations list is
part of the policy decision recorded on the receipt; when the verifier is given those
obligations (`required_obligations=("test_log","review_thread")`), the same bundle
returns INCOMPLETE with `missing evidence obligations: review_thread`.

**Fix shipped (same day):** mitigation 1 implemented in `verifier.py` — when the
caller supplies no `required_obligations`, the verifier now falls back to the
receipt-carried `decision.evidence_obligations` (signed, so an external tamperer
cannot shrink it). Regression test: `tests/adversarial/test_s26_pass_on_tampered.py::
test_attack_6_sign_then_strip_issuer_side` asserts the partial-strip bundle now
verifies INCOMPLETE with `missing evidence obligations`. 23/23 suite green.

**Remaining hardening (not blocking, honestly scoped):**
2. **Anchor signed receipt digests out-of-band** — append each receipt's envelope digest
   to the flight recorder at issuance; an auditor re-walks the chain and detects any
   later re-issued variant for the same `action_id`. This closes the residual
   *malicious key-holder* case (an issuer who also rewrites the obligations list and
   re-signs), which no receipt-local check can fully close.
3. Long-term: transparency-log witnessing (Sigstore-style) so re-issuance is globally
   visible. Explicitly out of v1 scope per the exclusion table.

**Severity rationale:** requires the key-holder (or platform) as attacker — insider
threat, not external. The claim layer, schema validator, and obligations mechanism each
independently downgrade the dishonest variants that were tested (full strip + COMPLETE
flag ⇒ schema FAIL; honest re-sign ⇒ INCOMPLETE).

## S2.7 — Redaction vs integrity
Commitments are **inside** the signed payload, so post-hoc salt/digest tampering breaks
the signature (attack 5). `RedactionCommitment.verify()` rejects forged plaintexts
(demo step 11). Note: the commitment binds plaintext+salt but carries no binding to the
`receipt_id`/`action_id`; a commitment could theoretically be transplanted between
receipts. Low severity (commitment still only opens to its true plaintext), but adding
`receipt_id` into the digest preimage is a cheap hardening.

## S2.8 — Service-account spoofing
`Actor.is_service_account` is `Literal[False]`; schema rejects `true` and the verifier
hard-FAILs on it (attack 3). The `HumanApproval.approver` is also an `Actor`, so a
service account cannot approve. **Held.** Out of scope here (by design): the *binding*
between `actor_id` strings and real identities is an enrollment/IAM problem, not a
receipt-schema problem — document at integration time.

## S3 — Policy engine & flight recorder
- Default DENY held on unknown action; glob matching is case-sensitive (no
  `DEPLOY.*`→`deploy.*` case bypass).
- DENY first-match still accumulates obligations from later matched rules (recorded
  for audit).
- IRREVERSIBLE + ALLOW rule ⇒ `requires_human_approval=True`, and the receipt schema
  refuses ALLOW-without-approval.
- Recorder: mid-log byte flip, tail truncation, and full frame-splice all detected
  (CRC + hash chain); hand-crafted seq jump produces honest `gaps` with chain intact;
  replay never re-yields executed idempotency keys; sync-marker lifecycle correct;
  non-log bytes rejected at header.

## Harness defect found during execution (fixed)
Step 9 (Article 12 conformance report) failed with `KeyError: 'entries'` because
`DEFAULT_CONFORMANCE` pointed at the legacy estate-owned profile
(`evidence/conformance/eu-ai-act-article-12.yaml`, a different schema), while the
canonical 11-entry profile is `eu-ai-act-article-12.v1.yaml`. Default corrected;
**12/12 steps now pass.** The legacy file should be tombstoned or regenerated in the
canonical shape — flagged, not deleted, in this review.

## What this review does NOT claim
- No production in-toto/DSSE path was attacked here (`InTotoDsseBackend` deps are
  optional; the demo backend was the target, clearly labeled non-production).
- No multi-threaded flock stress, no fsync-failure injection, no clock-rollback test
  (RFC 3161 / NTP fields are recorded-but-WEAK in the demo; strong-time path needs a
  live TSA).
- The verifier remains trusting of caller-supplied `required_obligations` (see S2.6-6).
