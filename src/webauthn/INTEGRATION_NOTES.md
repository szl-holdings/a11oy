# WebAuthn Human-in-the-Loop Attestation Integration Notes

## Standards References
- **W3C WebAuthn Level 3**: https://www.w3.org/TR/webauthn-3/
- **FIDO2 CTAP2**: https://fidoalliance.org/specs/fido-v2.0-ps-20190130/
- **Yubico Signing Pattern**: https://developers.yubico.com/WebAuthn/Concepts/Using_WebAuthn_for_Signing.html
- **COSE Algorithms**: https://www.iana.org/assignments/cose/cose.xhtml
- **SimpleWebAuthn**: https://simplewebauthn.dev/docs/

## Architecture
```
Cursor/Claude operator interface
         │ sensitive action detected
         ▼
mcpWebAuthnApprove() → returns AuthenticationOptions to browser
         │
         ▼
Browser: startAuthentication() from @simplewebauthn/browser
Touch ID / FIDO2 gesture
         │
         ▼
WebAuthn assertion (clientDataJSON + authenticatorData + ECDSA-P256 sig)
         │
         ▼
verifyAssertionAndEmitDSSE() → WebAuthnDSSESignature
         │
         ▼
augmentDSSEWithWebAuthn() → DSSE envelope with 2 signatures:
  1. HMAC-SHA256 (automated, machine identity)
  2. WebAuthn ECDSA-P256 (human, biometric/PIN-bound)
         │
         ▼
augmentReceiptWithWebAuthn() → JSONL receipt + humanAttestation block
         │
         ▼
submitDSSEToRekor() → Rekor entry with dual-signature envelope
```

## MCP Tool Integration

Two new MCP tools exposed to Cursor/Claude users:

### `webauthn_register`
```typescript
server.tool("webauthn_register", {
  operatorDID: z.string(),
  userName: z.string(),
}, async ({ operatorDID, userName }) => {
  const opts = mcpWebAuthnRegister(szlRP, operatorDID, userName);
  // Return to browser for startRegistration(@simplewebauthn/browser)
  return { registrationOptions: opts };
});
```

### `webauthn_approve`
```typescript
server.tool("webauthn_approve", {
  operatorDID: z.string(),
  receiptId: z.string(),
}, async ({ operatorDID, receiptId }) => {
  const receipt = await lookupReceipt(receiptId);
  const opts = mcpWebAuthnApprove(szlRP, operatorDID, receipt.envelope.payload);
  // Return to browser for startAuthentication()
  // After browser completes gesture, call verify_assertion tool:
  return { signingOptions: opts, pendingApproval: receiptId };
});
```

## Sensitive Action Policy (when to require WebAuthn)
Configure in `a11oy/src/webauthn/policy.ts`:

| Action | Require WebAuthn? | Reason |
|---|---|---|
| `deploy` to production | YES | Irreversible side effect |
| `key_rotation` | YES | Cryptographic identity change |
| `federation_cross_ref` | YES | Cross-org trust boundary |
| `validate` | NO | Automated quality gate |
| `audit_export` | YES | Data sovereignty |
| `deploy` to staging | NO | Reversible test env |

## STAGED-ADVISORY: Production Dependencies

```bash
# Server-side (Node.js Pepr/MCP):
npm install @simplewebauthn/server

# Browser-side (Cursor plugin / web UI):
npm install @simplewebauthn/browser

# Replace dev stubs:
# verifyRegistration → verifyRegistrationResponse from @simplewebauthn/server
# verifyAssertionAndEmitDSSE → verifyAuthenticationResponse from @simplewebauthn/server
```

## Security Properties
1. **Human presence**: UP flag verified — physical authenticator interaction required
2. **User verification**: UV flag verified — biometric/PIN required, not just tap
3. **Replay prevention**: signCount monotonically increasing; counter replay rejected
4. **Payload binding**: challenge = SHA-256(DSSE payload) — assertion is cryptographically
   bound to the specific receipt being approved, not just any receipt
5. **Origin binding**: clientDataJSON.origin checked — prevents cross-site relay attacks
6. **Additive, not substitutive**: WebAuthn sig appended alongside HMAC; both required
   for "dual-control" governance actions
